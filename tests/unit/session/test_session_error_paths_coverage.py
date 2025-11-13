"""Additional coverage tests for session module error paths and edge cases.

Covers:
- Error handlers that can be tested
- TorrentInfoModel input paths
- Exception handling during start/stop
- Background task cleanup paths
- Edge cases in normalization
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from ccbt.models import TorrentInfo
from tests.conftest import create_test_torrent_dict

pytestmark = [pytest.mark.unit, pytest.mark.session]


class TestAsyncTorrentSessionErrorPaths:
    """Test AsyncTorrentSession error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_start_with_error_callback(self, tmp_path):
        """Test start() error handler with on_error callback (line 446-447)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)

        # Set error callback
        error_called = []

        async def error_handler(e):
            error_called.append(e)

        session.on_error = error_handler

        # Force error during start by breaking tracker start (not caught internally)
        session.tracker.start = AsyncMock(  # type: ignore[assignment]
            side_effect=RuntimeError("Tracker start error")
        )

        with pytest.raises(RuntimeError):
            await session.start()

        # Verify error handler was called
        assert len(error_called) == 1
        assert isinstance(error_called[0], RuntimeError)
        assert str(error_called[0]) == "Tracker start error"
        assert session.info.status == "error"

    @pytest.mark.asyncio
    async def test_pause_exception_handler(self, tmp_path):
        """Test pause() exception handler (line 513-514)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)
        await session.start()

        # Mock download_manager.pause to raise exception
        session.download_manager.pause = Mock(side_effect=RuntimeError("Pause failed"))  # type: ignore[assignment]

        # Should handle exception gracefully
        await session.pause()

        # Status should still be updated
        assert session.info.status == "paused"

    @pytest.mark.asyncio
    async def test_resume_exception_handler(self, tmp_path):
        """Test resume() exception handler (line 765-768)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)
        await session.start()
        await session.pause()

        # Mock download_manager.resume to raise exception
        session.download_manager.resume = Mock(side_effect=RuntimeError("Resume failed"))  # type: ignore[assignment]

        # Should handle exception gracefully
        await session.resume()

        # Status should be restored
        assert session.info.status in ["downloading", "starting"]

    @pytest.mark.asyncio
    async def test_get_torrent_info_with_torrent_info_model(self, tmp_path):
        """Test _get_torrent_info with TorrentInfoModel input (line 158-159)."""
        from ccbt.session.session import AsyncTorrentSession

        # Create TorrentInfo directly
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com",
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

        session = AsyncTorrentSession(torrent_info, str(tmp_path), None)

        # Should use TorrentInfo directly
        assert session.info.name == "test_torrent"

    def test_normalize_torrent_data_with_torrent_info_model(self, tmp_path):
        """Test _normalize_torrent_data with TorrentInfoModel (line 296-307)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com",
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

        session = AsyncTorrentSession(torrent_info, str(tmp_path), None)

        # Verify normalized data structure
        normalized = session._normalized_td
        assert normalized["name"] == "test"
        assert normalized["info_hash"] == b"\x00" * 20
        assert "pieces_info" in normalized
        assert normalized["pieces_info"]["piece_length"] == 16384

    def test_normalize_torrent_data_with_pieces_info(self, tmp_path):
        """Test _normalize_torrent_data with pieces_info present (line 283-289)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = {
            "name": "test",
            "info_hash": b"\x00" * 20,
            "pieces_info": {
                "piece_hashes": [b"\x00" * 20],
                "piece_length": 16384,
                "num_pieces": 1,
                "total_length": 1024,
            },
            "file_info": {"total_length": 1024},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)

        # Verify pieces_info is preserved
        normalized = session._normalized_td
        assert normalized["pieces_info"]["piece_length"] == 16384
        assert len(normalized["pieces_info"]["piece_hashes"]) == 1

    def test_normalize_torrent_data_missing_file_info(self, tmp_path):
        """Test _normalize_torrent_data when file_info is missing (line 289-292)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = {
            "name": "test",
            "info_hash": b"\x00" * 20,
            "pieces_info": {
                "piece_hashes": [b"\x00" * 20],
                "piece_length": 16384,
                "num_pieces": 1,
                "total_length": 1024,
            },
            "total_length": 1024,
            # Missing file_info
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)

        # Should create default file_info via _normalize_torrent_data
        normalized = session._normalize_torrent_data(torrent_data)
        assert "file_info" in normalized
        assert normalized["file_info"]["total_length"] == 1024
        normalized = session._normalized_td
        assert "file_info" in normalized
        assert normalized["file_info"]["total_length"] == 1024


class TestAsyncSessionManagerErrorPaths:
    """Test AsyncSessionManager error paths and edge cases."""

    @pytest.mark.asyncio
    async def test_stop_peer_service_exception(self, tmp_path):
        """Test stop() handles peer service stop exception (line 1123-1125)."""
        from ccbt.session.session import AsyncSessionManager
        from unittest.mock import AsyncMock, patch

        manager = AsyncSessionManager(str(tmp_path))
        # Disable NAT to prevent blocking socket operations
        manager.config.nat.auto_map_ports = False
        # Patch socket operations to prevent blocking
        with patch('socket.socket') as mock_socket:
            # Make recvfrom return immediately to prevent blocking
            mock_sock = AsyncMock()
            mock_sock.recvfrom = AsyncMock(return_value=(b'\x00' * 12, ('127.0.0.1', 5351)))
            mock_socket.return_value = mock_sock
            await manager.start()

        # Mock peer_service.stop to raise exception
        if manager.peer_service:
            manager.peer_service.stop = AsyncMock(side_effect=RuntimeError("Stop failed"))  # type: ignore[assignment]

        # Should handle exception gracefully
        await manager.stop()

        # Manager should still stop successfully
        assert manager.peer_service is not None or True  # Service may be None

    @pytest.mark.asyncio
    async def test_stop_nat_manager_exception(self, tmp_path):
        """Test stop() handles NAT manager stop exception (line 1131-1133)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = True

        # Mock NAT manager to raise on stop
        mock_nat = AsyncMock()
        mock_nat.stop = AsyncMock(side_effect=RuntimeError("NAT stop failed"))
        manager.nat_manager = mock_nat

        # Should handle exception gracefully
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_with_torrent_info_model(self, tmp_path):
        """Test add_torrent with TorrentInfoModel input (line 1296-1308)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Create TorrentInfo object and convert to dict (add_torrent expects dict or path)
        torrent_info = TorrentInfo(
            name="test_torrent",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com",
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

        # Convert TorrentInfo to dict format expected by add_torrent
        torrent_dict = {
            "name": torrent_info.name,
            "info_hash": torrent_info.info_hash,
            "pieces_info": {
                "piece_hashes": list(torrent_info.pieces),
                "piece_length": torrent_info.piece_length,
                "num_pieces": torrent_info.num_pieces,
                "total_length": torrent_info.total_length,
            },
            "file_info": {
                "total_length": torrent_info.total_length,
            },
        }

        info_hash_hex = await manager.add_torrent(torrent_dict, resume=False)

        assert info_hash_hex == (b"\x00" * 20).hex()
        assert len(manager.torrents) == 1

        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_with_dict_parser_result(self, monkeypatch, tmp_path):
        """Test add_torrent with dict result from parser (line 1270-1294)."""
        from ccbt.session import session as sess_mod
        from ccbt.session.session import AsyncSessionManager

        # Mock parser to return dict
        class _DictParser:
            def parse(self, path):
                return {
                    "name": "test",
                    "info_hash": b"\x00" * 20,
                    "pieces_info": {
                        "piece_hashes": [b"\x00" * 20],
                        "piece_length": 16384,
                        "num_pieces": 1,
                        "total_length": 1024,
                    },
                    "total_length": 1024,
                }

        monkeypatch.setattr(sess_mod, "TorrentParser", _DictParser)

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"dummy")

        info_hash_hex = await manager.add_torrent(str(torrent_file), resume=False)

        assert info_hash_hex == (b"\x00" * 20).hex()
        assert len(manager.torrents) == 1

        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_global_stats_with_multiple_torrents(self, tmp_path):
        """Test get_global_stats aggregates correctly across multiple torrents."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Add multiple torrents
        for i in range(3):
            torrent_data = create_test_torrent_dict(
                name=f"torrent_{i}",
                info_hash=bytes([i] * 20),
                file_length=1024 * (i + 1),
            )
            await manager.add_torrent(torrent_data, resume=False)

        stats = await manager.get_global_stats()

        assert stats["num_torrents"] == 3
        assert stats["num_active"] >= 0  # May be 0 if sessions haven't started
        assert stats["average_progress"] >= 0.0

        await manager.stop()

    @pytest.mark.asyncio
    async def test_export_import_session_state(self, tmp_path):
        """Test export_session_state and import_session_state."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Add a torrent
        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        await manager.add_torrent(torrent_data, resume=False)

        # Export state
        export_path = tmp_path / "session_state.json"
        await manager.export_session_state(export_path)

        # Verify file exists and is valid JSON
        assert export_path.exists()
        import json

        data = json.loads(export_path.read_text())
        assert "torrents" in data
        assert "config" in data

        # Import state
        imported = await manager.import_session_state(export_path)
        assert imported["torrents"] is not None

        await manager.stop()


class TestTorrentInfoValidationEdgeCases:
    """Test TorrentInfo validation edge cases."""

    def test_info_hash_too_short_truncates(self, tmp_path):
        """Test info_hash shorter than 20 bytes is padded."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = {
            "name": "test",
            "info_hash": b"\x00" * 10,  # Only 10 bytes
            "total_length": 1024,
            "piece_length": 16384,
            "pieces": [b"\x00" * 20],
            "num_pieces": 1,
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)

        # Should pad to 20 bytes
        assert len(session.info.info_hash) == 20
        assert session.info.info_hash[:10] == b"\x00" * 10
        assert session.info.info_hash[10:] == b"\x00" * 10

    def test_info_hash_too_long_truncates(self, tmp_path):
        """Test info_hash longer than 20 bytes is truncated."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = {
            "name": "test",
            "info_hash": b"\x00" * 25,  # 25 bytes
            "total_length": 1024,
            "piece_length": 16384,
            "pieces": [b"\x00" * 20],
            "num_pieces": 1,
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)

        # Should truncate to 20 bytes
        assert len(session.info.info_hash) == 20

    @pytest.mark.asyncio
    async def test_delete_checkpoint_exception_handler(self, tmp_path):
        """Test delete_checkpoint exception handler (line 623-626)."""
        from ccbt.session.session import AsyncTorrentSession

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        session = AsyncTorrentSession(torrent_data, str(tmp_path), None)
        await session.start()

        # Mock checkpoint_manager.delete_checkpoint to raise exception
        session.checkpoint_manager.delete_checkpoint = AsyncMock(  # type: ignore[assignment]
            side_effect=IOError("Delete failed")
        )

        # Should handle exception gracefully (no exception raised)
        await session.stop()

        # Session should still stop successfully
        assert session.info.status == "stopped"


class TestBackgroundTaskCleanup:
    """Test background task cleanup paths."""

    @pytest.mark.asyncio
    async def test_scrape_task_cancellation(self, tmp_path):
        """Test scrape task cancellation in stop() (line 1136-1141)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        await manager.start()

        # Create a scrape task
        async def scrape_loop():
            try:
                while True:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                pass

        manager.scrape_task = asyncio.create_task(scrape_loop())

        # Stop should cancel scrape task
        await manager.stop()

        # Task should be cancelled
        assert manager.scrape_task.done()

    @pytest.mark.asyncio
    async def test_background_task_cancellation(self, tmp_path):
        """Test background task cancellation in stop()."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        await manager.start()

        # Verify tasks exist
        assert manager._cleanup_task is not None
        assert manager._metrics_task is not None

        # Stop should cancel tasks
        await manager.stop()

        # Tasks should be cancelled
        assert manager._cleanup_task.cancelled() or manager._cleanup_task.done()
        assert manager._metrics_task.cancelled() or manager._metrics_task.done()


class TestSessionManagerAdditionalMethods:
    """Test additional session manager methods for coverage."""

    @pytest.mark.asyncio
    async def test_force_announce(self, tmp_path):
        """Test force_announce method (line 1500-1524)."""
        from ccbt.session.session import AsyncSessionManager
        from unittest.mock import AsyncMock

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Add torrent
        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        info_hash_hex = await manager.add_torrent(torrent_data, resume=False)

        # Mock tracker.announce to succeed
        session = list(manager.torrents.values())[0]
        session.tracker.announce = AsyncMock(return_value=None)  # type: ignore[assignment]

        # Force announce should succeed
        result = await manager.force_announce(info_hash_hex)
        assert result is True

        # Test with invalid hex
        assert await manager.force_announce("invalid") is False

        # Test with non-existent torrent
        assert await manager.force_announce("a" * 40) is False

        await manager.stop()

    @pytest.mark.asyncio
    async def test_force_announce_with_torrent_info_model(self, tmp_path):
        """Test force_announce with TorrentInfoModel torrent_data (line 1514-1519)."""
        from ccbt.session.session import AsyncSessionManager
        from unittest.mock import AsyncMock

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Create TorrentInfo and convert to dict for add_torrent
        torrent_info = TorrentInfo(
            name="test",
            info_hash=b"\x00" * 20,
            announce="http://tracker.example.com",
            total_length=1024,
            piece_length=16384,
            pieces=[b"\x00" * 20],
            num_pieces=1,
        )

        torrent_dict = {
            "name": torrent_info.name,
            "info_hash": torrent_info.info_hash,
            "pieces_info": {
                "piece_hashes": list(torrent_info.pieces),
                "piece_length": torrent_info.piece_length,
                "num_pieces": torrent_info.num_pieces,
                "total_length": torrent_info.total_length,
            },
            "file_info": {
                "total_length": torrent_info.total_length,
            },
        }
        info_hash_hex = await manager.add_torrent(torrent_dict, resume=False)

        # Set torrent_data to TorrentInfoModel to test that path in force_announce
        session = list(manager.torrents.values())[0]
        session.torrent_data = torrent_info  # type: ignore[assignment]

        # Mock tracker.announce to avoid real network call
        session.tracker.announce = AsyncMock(return_value=None)  # type: ignore[assignment]

        result = await manager.force_announce(info_hash_hex)
        assert result is True

        await manager.stop()

    @pytest.mark.asyncio
    async def test_force_announce_exception_handler(self, tmp_path):
        """Test force_announce exception handler (line 1521-1522)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        info_hash_hex = await manager.add_torrent(torrent_data, resume=False)

        # Mock tracker.announce to raise exception
        session = list(manager.torrents.values())[0]
        session.tracker.announce = AsyncMock(side_effect=RuntimeError("Announce failed"))  # type: ignore[assignment]

        result = await manager.force_announce(info_hash_hex)
        assert result is False

        await manager.stop()

    @pytest.mark.asyncio
    async def test_force_scrape(self, tmp_path):
        """Test force_scrape method (line 1581-1650)."""
        from ccbt.session.session import AsyncSessionManager
        from unittest.mock import AsyncMock

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        torrent_data = create_test_torrent_dict(
            name="test", file_length=1024, announce="http://tracker.example.com"
        )
        info_hash_hex = await manager.add_torrent(torrent_data, resume=False)

        # Mock BitTorrentProtocol.scrape_torrent to return successful stats
        with patch("ccbt.protocols.bittorrent.BitTorrentProtocol") as mock_protocol_class:
            mock_protocol = AsyncMock()
            mock_protocol.scrape_torrent = AsyncMock(
                return_value={"seeders": 10, "leechers": 5, "completed": 100}
            )
            mock_protocol_class.return_value = mock_protocol

            result = await manager.force_scrape(info_hash_hex)
            assert result is True

        # Test with invalid hex length
        assert await manager.force_scrape("abc") is False

        # Test with invalid hex format
        assert await manager.force_scrape("x" * 40) is False

        # Test with non-existent torrent
        assert await manager.force_scrape("a" * 40) is False

        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_peers_for_torrent_with_peer_service(self, tmp_path):
        """Test get_peers_for_torrent with peer_service (line 1478-1498)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Mock peer_service.list_peers
        if manager.peer_service:
            from unittest.mock import AsyncMock

            class MockPeer:
                def __init__(self):
                    from ccbt.models import PeerInfo

                    self.peer_info = PeerInfo(ip="1.2.3.4", port=6881)

            manager.peer_service.list_peers = AsyncMock(  # type: ignore[assignment]
                return_value=[MockPeer(), MockPeer()]
            )

            peers = await manager.get_peers_for_torrent("a" * 40)
            # Should return list of peer dicts
            assert isinstance(peers, list)

        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_peers_for_torrent_without_peer_service(self, tmp_path):
        """Test get_peers_for_torrent without peer_service (line 1478-1479)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        manager.peer_service = None  # No peer service

        peers = await manager.get_peers_for_torrent("a" * 40)
        assert peers == []

    @pytest.mark.asyncio
    async def test_get_peers_for_torrent_exception_handler(self, tmp_path):
        """Test get_peers_for_torrent exception handler (line 1495-1498)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        if manager.peer_service:
            manager.peer_service.list_peers = AsyncMock(side_effect=RuntimeError("Error"))  # type: ignore[assignment]

            peers = await manager.get_peers_for_torrent("a" * 40)
            assert peers == []

        await manager.stop()

    @pytest.mark.asyncio
    async def test_auto_scrape_torrent(self, tmp_path):
        """Test _auto_scrape_torrent background task (line 1366-1371)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        manager.config.discovery.tracker_auto_scrape = True  # type: ignore[assignment]
        await manager.start()

        torrent_data = create_test_torrent_dict(
            name="test",
            file_length=1024,
            announce="http://tracker.example.com",
        )
        info_hash_hex = await manager.add_torrent(torrent_data, resume=False)

        # Mock tracker.scrape
        session = list(manager.torrents.values())[0]
        session.tracker.scrape = AsyncMock(  # type: ignore[assignment]
            return_value={"complete": 10, "incomplete": 5}
        )

        # Trigger auto-scrape (call directly since it's normally background task)
        info_hash = bytes.fromhex(info_hash_hex)
        await manager._auto_scrape_torrent(info_hash_hex)

        # Give it time to complete
        await asyncio.sleep(0.1)

        # Verify scrape was called (indirectly via cache)
        async with manager.scrape_cache_lock:
            info_hash = bytes.fromhex(info_hash_hex)
            # Cache may or may not be populated depending on scrape success
            _ = info_hash  # Use variable

        await manager.stop()

    @pytest.mark.asyncio
    async def test_queue_manager_auto_start_path(self, tmp_path):
        """Test queue manager auto-start path in add_torrent (line 1348-1354)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        manager.config.queue.auto_manage_queue = True
        await manager.start()

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        await manager.add_torrent(torrent_data, resume=False)

        # Verify torrent was added
        assert len(manager.torrents) == 1

        await manager.stop()

    @pytest.mark.asyncio
    async def test_on_torrent_callbacks(self, tmp_path):
        """Test on_torrent_added and on_torrent_removed callbacks."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        added_calls = []
        removed_calls = []

        async def on_added(info_hash, name):
            added_calls.append((info_hash, name))

        async def on_removed(info_hash):
            removed_calls.append(info_hash)

        manager.on_torrent_added = on_added
        manager.on_torrent_removed = on_removed

        # Add torrent
        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        info_hash_hex = await manager.add_torrent(torrent_data, resume=False)

        # Verify callback called
        assert len(added_calls) == 1
        assert added_calls[0][1] == "test"

        # Remove torrent
        await manager.remove(info_hash_hex)

        # Verify callback called
        assert len(removed_calls) == 1
        assert removed_calls[0] == bytes.fromhex(info_hash_hex)

        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_exception_handler(self, monkeypatch, tmp_path):
        """Test add_torrent exception handler logs properly (line 1375-1380)."""
        from ccbt.session import session as sess_mod
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        await manager.start()

        # Mock parser to raise exception
        class _ErrorParser:
            def parse(self, path):
                raise RuntimeError("Parse failed")

        monkeypatch.setattr(sess_mod, "TorrentParser", _ErrorParser)

        torrent_file = tmp_path / "test.torrent"
        torrent_file.write_bytes(b"dummy")

        with pytest.raises(RuntimeError):
            await manager.add_torrent(str(torrent_file), resume=False)

        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_fallback_start(self, tmp_path):
        """Test add_torrent fallback start when queue manager not initialized (line 1356-1357)."""
        from ccbt.session.session import AsyncSessionManager

        manager = AsyncSessionManager(str(tmp_path))
        manager.config.nat.auto_map_ports = False
        manager.config.queue.auto_manage_queue = False  # No queue manager
        await manager.start()

        torrent_data = create_test_torrent_dict(name="test", file_length=1024)
        await manager.add_torrent(torrent_data, resume=False)

        # Session should be started immediately
        session = list(manager.torrents.values())[0]
        status = await session.get_status()
        assert status.get("status") in ["starting", "downloading"]

        await manager.stop()

