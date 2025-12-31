"""Integration tests for refactored session lifecycle components.

Tests the integration of:
- TaskSupervisor
- SessionContext
- StatusAggregator
- CheckpointController
- LifecycleController
- PeerEventsBinder
- ManagerBackgroundTasks
- ScrapeManager
- TorrentAdditionHandler
- MagnetHandler
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.session]

from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession


class TestRefactoredSessionLifecycle:
    """Integration tests for refactored session lifecycle."""

    @pytest.fixture
    def tmp_dir(self, tmp_path: Path) -> Path:
        """Create temporary directory for downloads."""
        return tmp_path / "downloads"

    @pytest.fixture
    def manager(self, tmp_dir: Path) -> AsyncSessionManager:
        """Create session manager instance."""
        # Reset uTP socket manager singleton to avoid port conflicts
        from ccbt.transport.utp_socket import UTPSocketManager
        UTPSocketManager._instance = None  # Reset singleton
        
        manager = AsyncSessionManager(output_dir=str(tmp_dir))
        # Disable uTP to avoid port conflicts in tests
        manager.config.network.enable_utp = False
        # Disable network services to prevent hanging
        manager.config.discovery.enable_dht = False
        manager.config.nat.auto_map_ports = False
        # Use dynamic port allocation to avoid conflicts
        manager.config.network.listen_port = 0
        return manager

    @pytest.mark.asyncio
    async def test_session_with_task_supervisor(self, manager, tmp_dir: Path):
        """Test that session uses TaskSupervisor for task management."""
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "announce": "http://localhost:8080/announce",
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_dir), manager)

        # Verify TaskSupervisor is initialized
        assert hasattr(session, "_task_supervisor")
        assert session._task_supervisor is not None

        # Start session
        await session.start()

        # Verify tasks are tracked
        assert len(session._task_supervisor.tasks) > 0

        # Stop session
        await session.stop()

        # Verify tasks are cancelled
        await asyncio.sleep(0.1)  # Give tasks time to cancel
        for task in session._task_supervisor.tasks:
            assert task.done() or task.cancelled()

    @pytest.mark.asyncio
    async def test_session_with_session_context(self, manager, tmp_dir: Path):
        """Test that session uses SessionContext."""
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_dir), manager)

        # Verify SessionContext is initialized
        assert hasattr(session, "ctx")
        assert session.ctx is not None
        assert session.ctx.torrent_data == torrent_data
        assert session.ctx.config is not None

    @pytest.mark.asyncio
    async def test_session_with_status_aggregator(self, manager, tmp_dir: Path):
        """Test that session uses StatusAggregator."""
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_dir), manager)

        # Verify StatusAggregator is initialized
        assert hasattr(session, "status_aggregator")
        assert session.status_aggregator is not None

        # Get status
        status = await session.get_status()

        # Verify status structure
        assert "info_hash" in status
        assert "name" in status
        assert "status" in status

    @pytest.mark.asyncio
    async def test_session_with_checkpoint_controller(self, manager, tmp_dir: Path):
        """Test that session uses CheckpointController."""
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_dir), manager)

        # Verify CheckpointController is initialized
        assert hasattr(session, "checkpoint_controller")
        assert session.checkpoint_controller is not None

    @pytest.mark.asyncio
    async def test_session_with_lifecycle_controller(self, manager, tmp_dir: Path):
        """Test that session uses LifecycleController."""
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "announce": "http://localhost:8080/announce",
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        session = AsyncTorrentSession(torrent_data, str(tmp_dir), manager)

        # Verify LifecycleController is initialized
        assert hasattr(session, "lifecycle_controller")
        assert session.lifecycle_controller is not None

        # Test lifecycle methods
        await session.start()
        await session.pause()
        await session.resume()
        await session.stop()

    @pytest.mark.asyncio
    async def test_manager_with_background_tasks(self, manager):
        """Test that manager uses ManagerBackgroundTasks."""
        # Start manager
        await manager.start()

        # Verify ManagerBackgroundTasks is initialized
        assert hasattr(manager, "background_tasks")
        assert manager.background_tasks is not None

        # Verify background tasks are running
        assert manager._cleanup_task is not None
        assert manager._metrics_task is not None

        # Stop manager
        await manager.stop()

    @pytest.mark.asyncio
    async def test_manager_with_scrape_manager(self, manager):
        """Test that manager uses ScrapeManager."""
        # Verify ScrapeManager is initialized
        assert hasattr(manager, "scrape_manager")
        assert manager.scrape_manager is not None

    @pytest.mark.asyncio
    async def test_manager_with_torrent_addition_handler(self, manager):
        """Test that manager uses TorrentAdditionHandler."""
        # Verify TorrentAdditionHandler is initialized
        assert hasattr(manager, "torrent_addition_handler")
        assert manager.torrent_addition_handler is not None

    @pytest.mark.asyncio
    async def test_add_torrent_with_handler(self, manager, tmp_dir: Path, monkeypatch):
        """Test adding torrent using TorrentAdditionHandler."""
        # CRITICAL FIX: Add network mocking to prevent timeout
        # Disable NAT auto port mapping to prevent 60s wait
        monkeypatch.setenv("CCBT_NAT_AUTO_MAP_PORTS", "0")
        # Disable DHT to prevent network initialization  
        monkeypatch.setenv("CCBT_ENABLE_DHT", "0")
        
        # Mock AsyncTrackerClient at class level to prevent network calls
        mock_tracker = Mock()
        mock_tracker.start = AsyncMock(return_value=None)
        mock_tracker.stop = AsyncMock(return_value=None)
        mock_tracker.announce_to_multiple = AsyncMock(return_value=[])
        mock_tracker._session_manager = None
        
        # Configure manager to disable network services
        manager.config.nat.auto_map_ports = False  # Disable NAT to prevent blocking
        manager.config.network.enable_tcp = False  # Disable TCP server to prevent port conflicts
        manager.config.discovery.enable_dht = False  # Disable DHT to prevent network initialization
        
        # Mock heavy initialization methods to prevent hangs
        manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
        manager._make_tcp_server = lambda: None  # type: ignore[method-assign]
        
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        # Mock DHT client and tracker client to avoid network initialization
        with patch.object(manager, "_make_dht_client", return_value=None):
            with patch("ccbt.session.session.AsyncTrackerClient", return_value=mock_tracker):
                # Patch _wait_for_starting_session to return immediately (don't wait for status change)
                from ccbt.session.torrent_addition import TorrentAdditionHandler
                async def mock_wait_for_starting_session(self, session):
                    """Mock that returns immediately without waiting."""
                    # Set status to 'downloading' to allow test to proceed
                    if hasattr(session, 'info'):
                        session.info.status = "downloading"
                    return
                
                with patch.object(TorrentAdditionHandler, '_wait_for_starting_session', mock_wait_for_starting_session):
                    # Start manager
                    await manager.start()

                    # Add torrent
                    info_hash = await manager.add_torrent(torrent_data, str(tmp_dir))

                    # Verify torrent was added
                    assert info_hash == (b"x" * 20).hex()
                    assert b"x" * 20 in manager.torrents

                    # Stop manager
                    await manager.stop()

    @pytest.mark.asyncio
    async def test_session_lifecycle_sequence(self, manager, tmp_dir: Path, monkeypatch):
        """Test complete session lifecycle sequence."""
        # Disable NAT auto port mapping to prevent 60s wait
        monkeypatch.setenv("CCBT_NAT_AUTO_MAP_PORTS", "0")
        # Disable DHT to prevent network initialization  
        monkeypatch.setenv("CCBT_ENABLE_DHT", "0")
        
        # Mock AsyncTrackerClient to prevent network calls
        from unittest.mock import AsyncMock, MagicMock
        mock_tracker = MagicMock()
        mock_tracker.start = AsyncMock(return_value=None)
        mock_tracker.stop = AsyncMock(return_value=None)
        mock_tracker.announce_to_multiple = AsyncMock(return_value=[])
        mock_tracker._session_manager = None
        
        # Mock heavy initialization methods to prevent hangs
        manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
        manager._make_tcp_server = lambda: None  # type: ignore[method-assign]
        
        torrent_data = {
            "name": "test_torrent",
            "info_hash": b"x" * 20,
            "announce": "http://localhost:8080/announce",
            "pieces_info": {
                "num_pieces": 1,
                "piece_length": 16384,
                "piece_hashes": [b"x" * 20],
                "total_length": 16384,
            },
            "file_info": {"total_length": 16384},
        }

        # Mock DHT client and tracker client to avoid network initialization
        with patch.object(manager, "_make_dht_client", return_value=None):
            with patch("ccbt.session.session.AsyncTrackerClient", return_value=mock_tracker):
                # Patch _wait_for_starting_session to return immediately (don't wait for status change)
                from ccbt.session.torrent_addition import TorrentAdditionHandler
                async def mock_wait_for_starting_session(self, session):
                    """Mock that returns immediately without waiting."""
                    # Set status to 'downloading' to allow test to proceed
                    if hasattr(session, 'info'):
                        session.info.status = "downloading"
                    return
                
                with patch.object(TorrentAdditionHandler, '_wait_for_starting_session', mock_wait_for_starting_session):
                    # Start manager
                    await manager.start()

                    # Add and start torrent
                    info_hash = await manager.add_torrent(torrent_data, str(tmp_dir))
                    session = manager.torrents[b"x" * 20]

                    # Verify session started
                    status = await session.get_status()
                    assert status["status"] in ("downloading", "seeding", "stopped")

                    # Pause
                    await session.pause()
                    status = await session.get_status()
                    assert status["status"] == "paused"

                    # Resume
                    await session.resume()
                    status = await session.get_status()
                    assert status["status"] in ("downloading", "seeding", "stopped")

                    # Stop
                    await session.stop()
                    status = await session.get_status()
                    assert status["status"] == "stopped"

                    # Stop manager
                    await manager.stop()


















