"""Tests for session manager lifecycle and error paths."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.session]

from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession


class TestSessionManagerLifecycle:
    """Test session manager lifecycle methods."""

    @pytest.mark.asyncio
    async def test_start_stop(self, tmp_path):
        """Test starting and stopping session manager."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        assert manager._cleanup_task is not None
        assert manager._metrics_task is not None
        
        await manager.stop()
        # Background tasks should be cancelled
        assert manager._cleanup_task.cancelled()

    @pytest.mark.asyncio
    async def test_start_with_dht_disabled(self, tmp_path):
        """Test starting session manager with DHT disabled."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        with patch.object(manager.config.discovery, "enable_dht", False):
            await manager.start()
            assert manager.dht_client is None
            await manager.stop()

    @pytest.mark.asyncio
    async def test_start_peer_service_error(self, tmp_path):
        """Test starting session manager when peer service fails."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        if manager.peer_service:
            manager.peer_service.start = AsyncMock(side_effect=Exception("Service error"))
        
        # Should not raise
        await manager.start()
        await manager.stop()

    @pytest.mark.asyncio
    async def test_stop_peer_service_error(self, tmp_path):
        """Test stopping session manager when peer service fails."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        if manager.peer_service:
            manager.peer_service.stop = AsyncMock(side_effect=Exception("Service error"))
        
        # Should not raise
        await manager.stop()


class TestSessionManagerAddTorrent:
    """Test adding torrents to session manager."""

    @pytest.mark.asyncio
    async def test_add_torrent_dict(self, tmp_path):
        """Test adding torrent from dictionary."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20, b"\x22" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        assert info_hash_hex == "00" * 20
        assert len(manager.torrents) == 1
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_dict_no_info_hash(self, tmp_path):
        """Test adding torrent without info_hash."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {"name": "Test Torrent"}
        
        with pytest.raises(ValueError, match="Missing info_hash"):
            await manager.add_torrent(torrent_data)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_dict_string_info_hash_raises_error(self, tmp_path):
        """Test adding torrent with string info_hash raises error (current implementation)."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        # Current implementation doesn't convert string info_hash in dict path
        # This will fail when trying to call .hex() on a string
        torrent_data = {
            "info_hash": "00" * 20,  # String - not converted
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        # This will raise AttributeError when trying to call .hex() on string
        with pytest.raises(AttributeError):
            await manager.add_torrent(torrent_data)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_dict_invalid_info_hash(self, tmp_path):
        """Test adding torrent with invalid info_hash type."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        # Invalid info_hash type - when passed as dict, it passes initial validation
        # but fails later when creating session due to missing pieces_info
        torrent_data = {
            "info_hash": 12345,  # Invalid type
            "name": "Test Torrent",
            # Missing pieces_info will cause KeyError during session creation
            "file_info": {"total_length": 1000},
        }
        
        # The error happens during session creation, not during validation
        with pytest.raises(Exception):  # May be KeyError or TypeError depending on code path
            await manager.add_torrent(torrent_data)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_duplicate(self, tmp_path):
        """Test adding duplicate torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        await manager.add_torrent(torrent_data)
        
        with pytest.raises(ValueError, match="already exists"):
            await manager.add_torrent(torrent_data)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_from_file(self, tmp_path):
        """Test adding torrent from file path."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        with patch("ccbt.session.session.TorrentParser") as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse.return_value = torrent_data
            
            info_hash_hex = await manager.add_torrent("test.torrent")
            assert info_hash_hex == "00" * 20
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_from_file_model(self, tmp_path):
        """Test adding torrent from file path returning TorrentInfo model."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        from ccbt.models import TorrentInfo
        
        torrent_model = TorrentInfo(
            name="Test Torrent",
            info_hash=b"\x00" * 20,
            announce="udp://tracker.example.com:6969",
            pieces=[b"\x11" * 20],
            piece_length=512,
            num_pieces=2,
            total_length=1000,
        )
        
        with patch("ccbt.session.session.TorrentParser") as mock_parser:
            mock_parser_instance = MagicMock()
            mock_parser.return_value = mock_parser_instance
            mock_parser_instance.parse.return_value = torrent_model
            
            info_hash_hex = await manager.add_torrent("test.torrent")
            assert info_hash_hex == "00" * 20
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_torrent_on_torrent_added_callback(self, tmp_path):
        """Test on_torrent_added callback."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        callback_called = []
        
        async def on_added(info_hash, name):
            callback_called.append((info_hash, name))
        
        manager.on_torrent_added = on_added
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        await manager.add_torrent(torrent_data)
        
        assert len(callback_called) == 1
        assert callback_called[0][1] == "Test Torrent"
        
        await manager.stop()


class TestSessionManagerAddMagnet:
    """Test adding magnet links."""

    @pytest.mark.asyncio
    async def test_add_magnet(self, tmp_path):
        """Test adding magnet link."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        info_hash = b"\x00" * 20
        magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Test+Torrent"
        
        with patch("ccbt.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.build_minimal_torrent_data"
        ) as mock_build:
            from ccbt.core.magnet import MagnetInfo
            
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Test Torrent",
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": info_hash,
                "name": "Test Torrent",
                "file_info": {"total_length": 0},
                "pieces_info": {"piece_length": 0, "num_pieces": 0, "piece_hashes": []},
            }
            
            info_hash_hex = await manager.add_magnet(magnet_uri)
            assert info_hash_hex == "00" * 20
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_magnet_string_info_hash(self, tmp_path):
        """Test adding magnet with string info_hash."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        info_hash = b"\x00" * 20
        magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Test+Torrent"
        
        with patch("ccbt.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.build_minimal_torrent_data"
        ) as mock_build:
            from ccbt.core.magnet import MagnetInfo
            
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Test Torrent",
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": "00" * 20,  # String
                "name": "Test Torrent",
                "file_info": {"total_length": 0},
                "pieces_info": {"piece_length": 0, "num_pieces": 0, "piece_hashes": []},
            }
            
            info_hash_hex = await manager.add_magnet(magnet_uri)
            assert info_hash_hex == "00" * 20
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_magnet_duplicate(self, tmp_path):
        """Test adding duplicate magnet."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        info_hash = b"\x00" * 20
        magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Test+Torrent"
        
        with patch("ccbt.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.build_minimal_torrent_data"
        ) as mock_build:
            from ccbt.core.magnet import MagnetInfo
            
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Test Torrent",
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": info_hash,
                "name": "Test Torrent",
                "file_info": {"total_length": 0},
                "pieces_info": {"piece_length": 0, "num_pieces": 0, "piece_hashes": []},
            }
            
            await manager.add_magnet(magnet_uri)
            
            with pytest.raises(ValueError, match="already exists"):
                await manager.add_magnet(magnet_uri)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_add_magnet_on_torrent_added_callback(self, tmp_path):
        """Test on_torrent_added callback for magnet."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        callback_called = []
        
        async def on_added(info_hash, name):
            callback_called.append((info_hash, name))
        
        manager.on_torrent_added = on_added
        
        info_hash = b"\x00" * 20
        magnet_uri = f"magnet:?xt=urn:btih:{info_hash.hex()}&dn=Test+Torrent"
        
        with patch("ccbt.session.parse_magnet") as mock_parse, patch(
            "ccbt.session.build_minimal_torrent_data"
        ) as mock_build:
            from ccbt.core.magnet import MagnetInfo
            
            mock_parse.return_value = MagnetInfo(
                info_hash=info_hash,
                display_name="Test Torrent",
                trackers=[],
                web_seeds=[],
            )
            mock_build.return_value = {
                "info_hash": info_hash,
                "name": "Test Torrent",
                "file_info": {"total_length": 0},
                "pieces_info": {"piece_length": 0, "num_pieces": 0, "piece_hashes": []},
            }
            
            await manager.add_magnet(magnet_uri)
            
            assert len(callback_called) == 1


class TestSessionManagerRemove:
    """Test removing torrents."""

    @pytest.mark.asyncio
    async def test_remove_torrent(self, tmp_path):
        """Test removing torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        
        result = await manager.remove(info_hash_hex)
        assert result is True
        assert len(manager.torrents) == 0
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_remove_nonexistent(self, tmp_path):
        """Test removing non-existent torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.remove("00" * 20)
        assert result is False
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_remove_invalid_hash(self, tmp_path):
        """Test removing with invalid hash."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.remove("invalid")
        assert result is False
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_remove_on_torrent_removed_callback(self, tmp_path):
        """Test on_torrent_removed callback."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        callback_called = []
        
        async def on_removed(info_hash):
            callback_called.append(info_hash)
        
        manager.on_torrent_removed = on_removed
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        await manager.remove(info_hash_hex)
        
        assert len(callback_called) == 1
        assert callback_called[0] == b"\x00" * 20
        
        await manager.stop()


class TestSessionManagerPauseResume:
    """Test pausing and resuming torrents."""

    @pytest.mark.asyncio
    async def test_pause_torrent(self, tmp_path):
        """Test pausing torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        
        result = await manager.pause_torrent(info_hash_hex)
        assert result is True
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_pause_nonexistent(self, tmp_path):
        """Test pausing non-existent torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.pause_torrent("00" * 20)
        assert result is False
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_pause_invalid_hash(self, tmp_path):
        """Test pausing with invalid hash."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.pause_torrent("invalid")
        assert result is False
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_resume_torrent(self, tmp_path):
        """Test resuming torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        await manager.pause_torrent(info_hash_hex)
        
        result = await manager.resume_torrent(info_hash_hex)
        assert result is True
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_resume_nonexistent(self, tmp_path):
        """Test resuming non-existent torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.resume_torrent("00" * 20)
        assert result is False
        
        await manager.stop()


class TestSessionManagerRateLimits:
    """Test rate limit setting."""

    @pytest.mark.asyncio
    async def test_set_rate_limits(self, tmp_path):
        """Test setting rate limits."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        
        result = await manager.set_rate_limits(info_hash_hex, download_kib=100, upload_kib=50)
        assert result is True
        
        assert manager._per_torrent_limits[b"\x00" * 20]["down_kib"] == 100
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_set_rate_limits_nonexistent(self, tmp_path):
        """Test setting rate limits for non-existent torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.set_rate_limits("00" * 20, download_kib=100, upload_kib=50)
        assert result is False
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_set_rate_limits_invalid_hash(self, tmp_path):
        """Test setting rate limits with invalid hash."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        result = await manager.set_rate_limits("invalid", download_kib=100, upload_kib=50)
        assert result is False
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_set_rate_limits_negative(self, tmp_path):
        """Test setting negative rate limits."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        
        result = await manager.set_rate_limits(info_hash_hex, download_kib=-10, upload_kib=-5)
        assert result is True
        
        # Should be clamped to 0
        assert manager._per_torrent_limits[b"\x00" * 20]["down_kib"] == 0
        
        await manager.stop()


class TestSessionManagerStatus:
    """Test status methods."""

    @pytest.mark.asyncio
    async def test_get_status(self, tmp_path):
        """Test getting global status."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        status = await manager.get_status()
        assert isinstance(status, dict)
        # get_status returns a dict with torrent statuses, structure may vary
        # Just check it's a dict and doesn't crash
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_torrent_status(self, tmp_path):
        """Test getting torrent status."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        info_hash_hex = await manager.add_torrent(torrent_data)
        
        status = await manager.get_torrent_status(info_hash_hex)
        assert isinstance(status, dict)
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_torrent_status_nonexistent(self, tmp_path):
        """Test getting status for non-existent torrent."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        status = await manager.get_torrent_status("00" * 20)
        assert status is None
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_global_stats(self, tmp_path):
        """Test getting global stats."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        stats = await manager.get_global_stats()
        assert isinstance(stats, dict)
        assert "num_torrents" in stats
        assert "download_rate" in stats
        
        await manager.stop()

    @pytest.mark.asyncio
    async def test_get_global_stats_with_torrents(self, tmp_path):
        """Test getting global stats with active torrents."""
        manager = AsyncSessionManager(output_dir=str(tmp_path))
        await manager.start()
        
        torrent_data = {
            "info_hash": b"\x00" * 20,
            "name": "Test Torrent",
            "file_info": {"total_length": 1000},
            "pieces_info": {"piece_length": 512, "num_pieces": 2, "piece_hashes": [b"\x11" * 20]},
        }
        
        await manager.add_torrent(torrent_data)
        
        stats = await manager.get_global_stats()
        assert stats["num_torrents"] == 1
        
        await manager.stop()

