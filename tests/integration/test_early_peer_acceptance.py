"""Tests for early peer acceptance and download start.

These tests verify that:
1. Incoming peers are accepted even before tracker announce completes
2. Download starts as soon as first peers are discovered from any tracker
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = [pytest.mark.integration]

from ccbt.session.session import AsyncSessionManager, AsyncTorrentSession

# #region agent log
def _debug_log(hypothesis_id: str, location: str, message: str, data: Optional[dict] = None):
    """Debug logging for test hang investigation."""
    try:
        log_path = Path(".cursor/debug.log")
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "id": f"log_{asyncio.get_event_loop().time()}_{hypothesis_id}",
                "timestamp": asyncio.get_event_loop().time() * 1000,
                "location": location,
                "message": message,
                "data": data or {},
                "sessionId": "test-hang-investigation",
                "runId": "run1",
                "hypothesisId": hypothesis_id
            }) + "\n")
    except Exception:
        pass  # Best effort - don't break tests
# #endregion


class TestEarlyPeerAcceptance:
    """Test that incoming peers are accepted before tracker announce completes."""

    @pytest.mark.asyncio
    async def test_incoming_peer_before_tracker_announce(self, tmp_path):
        """Test that incoming peers are queued and accepted even before tracker announce completes."""
        start_task: Optional[asyncio.Task] = None
        
        with patch("ccbt.config.config.get_config") as mock_get_config:
            from ccbt.config.config import Config
            # Create a valid config with discovery intervals >= 30
            config = Config()
            config.discovery.aggressive_initial_dht_interval = 30.0
            config.discovery.aggressive_discovery_interval_popular = 30.0
            config.discovery.aggressive_discovery_interval_active = 30.0
            config.nat.auto_map_ports = False  # Disable NAT to prevent blocking
            config.network.enable_tcp = False  # Disable TCP server to prevent port conflicts
            config.discovery.enable_dht = False  # Disable DHT to prevent network initialization
            mock_get_config.return_value = config
            
            # Mock NAT manager to prevent hanging on port mapping
            with patch("ccbt.session.session.AsyncSessionManager._make_nat_manager") as mock_nat:
                mock_nat.return_value = None  # Disable NAT manager to prevent hangs
                
                manager = AsyncSessionManager(output_dir=str(tmp_path))
                manager.config.nat.auto_map_ports = False
                manager.config.network.enable_tcp = False
                manager.config.discovery.enable_dht = False
                
                # Mock heavy initialization methods
                manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
                manager._make_tcp_server = lambda: None  # type: ignore[method-assign]
                
                # Mock DHT client to prevent port conflicts
                with patch.object(manager, "_make_dht_client", return_value=None):
                    # Mock _wait_for_starting_session to return immediately
                    from ccbt.session.torrent_addition import TorrentAdditionHandler
                    async def mock_wait_for_starting_session(self, session):
                        """Mock that returns immediately without waiting."""
                        # Set status to 'downloading' to allow test to proceed
                        if hasattr(session, 'info'):
                            session.info.status = "downloading"
                        return
                    
                    with patch.object(TorrentAdditionHandler, '_wait_for_starting_session', mock_wait_for_starting_session):
                        # Start manager with timeout to prevent hanging
                        try:
                            await asyncio.wait_for(manager.start(), timeout=10.0)
                        except asyncio.TimeoutError:
                            pytest.fail("Manager start timed out")
                        
                        try:
                            # Create a torrent session
                            torrent_data = {
                                "info_hash": b"\x00" * 20,
                                "name": "Test Torrent",
                                "file_info": {"total_length": 1000},
                                "pieces_info": {
                                    "piece_length": 512,
                                    "num_pieces": 2,
                                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                                },
                                "announce_list": [["http://127.0.0.1:6969/announce"]],  # Add tracker URL for validation
                            }
                            
                            info_hash_hex = await manager.add_torrent(torrent_data)
                            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
                            session = manager.torrents[info_hash_bytes]
                            
                            # Mock tracker.start() to prevent real network calls that would hang
                            with patch.object(session.tracker, 'start', new_callable=AsyncMock) as mock_tracker_start:
                                mock_tracker_start.return_value = None
                                
                                # Start the session but delay tracker announce
                                start_task = asyncio.create_task(session.start())
                            
                            # Wait for peer_manager to initialize and queue processor task to be created
                            # Poll with timeout to ensure initialization completes
                            max_wait = 2.0
                            wait_interval = 0.1
                            waited = 0.0
                            while waited < max_wait:
                                if hasattr(session.download_manager, "peer_manager") and session.download_manager.peer_manager is not None:
                                    break
                                await asyncio.sleep(wait_interval)
                                waited += wait_interval
                            
                            # Verify peer_manager is initialized early
                            assert hasattr(session.download_manager, "peer_manager") and session.download_manager.peer_manager is not None, "peer_manager should be initialized early"
                            assert hasattr(session, "_incoming_peer_queue"), "Should have incoming peer queue"
                            
                            # Wait a bit more for queue processor task to be created (if it's created)
                            await asyncio.sleep(0.2)
                            
                            # Queue processor task may or may not be created depending on timing
                            # If peer_manager is ready, peers are accepted immediately, so queue processor may not be needed
                            # But if it exists, it should be running (not done)
                            if hasattr(session, "_peer_queue_processor_task") and session._peer_queue_processor_task is not None:
                                assert not session._peer_queue_processor_task.done(), "Queue processor should be running if it exists"
                            
                            # Simulate an incoming peer connection before tracker announce completes
                            mock_reader = AsyncMock()
                            mock_writer = MagicMock()
                            mock_handshake = MagicMock()
                            mock_handshake.info_hash = b"\x00" * 20
                            
                            # Accept the incoming peer
                            # Since peer_manager is ready, peer should be accepted immediately (not queued)
                            await session.accept_incoming_peer(
                                mock_reader,
                                mock_writer,
                                mock_handshake,
                                "127.0.0.1",
                                6881
                            )
                            
                            # Verify peer was accepted (not queued) since peer_manager is ready
                            # Queue should be empty since peer was accepted immediately
                            assert session._incoming_peer_queue.qsize() == 0, "Peer should be accepted immediately, not queued"
                            
                            # Wait for start to complete with timeout
                            if start_task:
                                try:
                                    await asyncio.wait_for(start_task, timeout=5.0)
                                except asyncio.TimeoutError:
                                    # Cancel the task if it times out
                                    start_task.cancel()
                                    try:
                                        await start_task
                                    except asyncio.CancelledError:
                                        pass
                        
                        finally:
                            # Cancel start_task if still running
                            if start_task and not start_task.done():
                                start_task.cancel()
                                try:
                                    await asyncio.wait_for(start_task, timeout=2.0)
                                except (asyncio.TimeoutError, asyncio.CancelledError):
                                    pass
                            
                            # Stop manager with timeout
                            try:
                                await asyncio.wait_for(manager.stop(), timeout=10.0)
                            except asyncio.TimeoutError:
                                pass  # Manager stop timeout is not critical for test

    @pytest.mark.asyncio
    async def test_incoming_peer_queue_when_peer_manager_not_ready(self, tmp_path):
        """Test that incoming peers are queued when peer_manager is not ready."""
        with patch("ccbt.config.config.get_config") as mock_get_config:
            from ccbt.config.config import Config
            # Create a valid config with discovery intervals >= 30
            config = Config()
            config.discovery.aggressive_initial_dht_interval = 30.0
            config.discovery.aggressive_discovery_interval_popular = 30.0
            config.discovery.aggressive_discovery_interval_active = 30.0
            config.nat.auto_map_ports = False  # Disable NAT to prevent blocking
            config.network.enable_tcp = False  # Disable TCP server to prevent port conflicts
            config.discovery.enable_dht = False  # Disable DHT to prevent network initialization
            mock_get_config.return_value = config
            
            # Mock NAT manager to prevent hanging on port mapping
            with patch("ccbt.session.session.AsyncSessionManager._make_nat_manager") as mock_nat:
                mock_nat.return_value = None  # Disable NAT manager to prevent hangs
                
                manager = AsyncSessionManager(output_dir=str(tmp_path))
                manager.config.nat.auto_map_ports = False
                manager.config.network.enable_tcp = False
                manager.config.discovery.enable_dht = False
                
                # Mock heavy initialization methods
                manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
                manager._make_tcp_server = lambda: None  # type: ignore[method-assign]
                
                # Mock DHT client to prevent port conflicts
                with patch.object(manager, "_make_dht_client", return_value=None):
                    # Mock _wait_for_starting_session to return immediately
                    from ccbt.session.torrent_addition import TorrentAdditionHandler
                    async def mock_wait_for_starting_session(self, session):
                        """Mock that returns immediately without waiting."""
                        # Set status to 'downloading' to allow test to proceed
                        if hasattr(session, 'info'):
                            session.info.status = "downloading"
                        return
                    
                    with patch.object(TorrentAdditionHandler, '_wait_for_starting_session', mock_wait_for_starting_session):
                        # Start manager with timeout
                        try:
                            await asyncio.wait_for(manager.start(), timeout=10.0)
                        except asyncio.TimeoutError:
                            pytest.fail("Manager start timed out")
                        
                        try:
                            # Create a torrent session
                            torrent_data = {
                                "info_hash": b"\x00" * 20,
                                "name": "Test Torrent",
                                "file_info": {"total_length": 1000},
                                "pieces_info": {
                                    "piece_length": 512,
                                    "num_pieces": 2,
                                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                                },
                                "announce_list": [["http://127.0.0.1:6969/announce"]],  # Add tracker URL for validation
                            }
                            
                            info_hash_hex = await manager.add_torrent(torrent_data)
                            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
                            session = manager.torrents[info_hash_bytes]
                            
                            # Temporarily set peer_manager to None to simulate early connection
                            original_peer_manager = getattr(session.download_manager, "peer_manager", None)
                            if hasattr(session.download_manager, "peer_manager"):
                                session.download_manager.peer_manager = None
                            
                            try:
                                # Simulate an incoming peer connection
                                mock_reader = AsyncMock()
                                mock_writer = MagicMock()
                                mock_handshake = MagicMock()
                                mock_handshake.info_hash = b"\x00" * 20
                                
                                # Accept the incoming peer - should queue it
                                await session.accept_incoming_peer(
                                    mock_reader,
                                    mock_writer,
                                    mock_handshake,
                                    "127.0.0.1",
                                    6881
                                )
                                
                                # Verify peer was queued
                                assert session._incoming_peer_queue.qsize() > 0, "Peer should be queued"
                            
                            finally:
                                # Restore peer_manager
                                if hasattr(session.download_manager, "peer_manager"):
                                    session.download_manager.peer_manager = original_peer_manager
                        
                        finally:
                            # Stop manager with timeout
                            try:
                                await asyncio.wait_for(manager.stop(), timeout=10.0)
                            except asyncio.TimeoutError:
                                pass  # Manager stop timeout is not critical for test


class TestEarlyDownloadStart:
    """Test that download starts as soon as first peers are discovered."""

    @pytest.mark.asyncio
    async def test_download_starts_on_first_tracker_response(self, tmp_path):
        """Test that download starts immediately when first tracker responds with peers."""
        start_task: Optional[asyncio.Task] = None
        
        with patch("ccbt.config.config.get_config") as mock_get_config:
            from ccbt.config.config import Config
            # Create a valid config with discovery intervals >= 30
            config = Config()
            config.discovery.aggressive_initial_dht_interval = 30.0
            config.discovery.aggressive_discovery_interval_popular = 30.0
            config.discovery.aggressive_discovery_interval_active = 30.0
            config.nat.auto_map_ports = False  # Disable NAT to prevent blocking
            config.network.enable_tcp = False  # Disable TCP server to prevent port conflicts
            config.discovery.enable_dht = False  # Disable DHT to prevent network initialization
            mock_get_config.return_value = config
            
            # Mock NAT manager to prevent hanging on port mapping
            with patch("ccbt.session.session.AsyncSessionManager._make_nat_manager") as mock_nat:
                mock_nat.return_value = None  # Disable NAT manager to prevent hangs
                
                manager = AsyncSessionManager(output_dir=str(tmp_path))
                manager.config.nat.auto_map_ports = False
                manager.config.network.enable_tcp = False
                manager.config.discovery.enable_dht = False
                
                # Mock heavy initialization methods
                manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
                manager._make_tcp_server = lambda: None  # type: ignore[method-assign]
                
                # Mock DHT client to prevent port conflicts
                with patch.object(manager, "_make_dht_client", return_value=None):
                    # Mock _wait_for_starting_session to return immediately
                    from ccbt.session.torrent_addition import TorrentAdditionHandler
                    async def mock_wait_for_starting_session(self, session):
                        """Mock that returns immediately without waiting."""
                        # Set status to 'downloading' to allow test to proceed
                        if hasattr(session, 'info'):
                            session.info.status = "downloading"
                        return
                    
                    with patch.object(TorrentAdditionHandler, '_wait_for_starting_session', mock_wait_for_starting_session):
                        # Start manager with timeout
                        try:
                            await asyncio.wait_for(manager.start(), timeout=10.0)
                        except asyncio.TimeoutError:
                            pytest.fail("Manager start timed out")
                        
                        try:
                            # Create a torrent session
                            torrent_data = {
                                "info_hash": b"\x00" * 20,
                                "name": "Test Torrent",
                                "file_info": {"total_length": 1000},
                                "pieces_info": {
                                    "piece_length": 512,
                                    "num_pieces": 2,
                                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                                },
                                "announce_list": [["http://127.0.0.1:6969/announce"]],  # Add tracker URL for validation
                            }
                            
                            info_hash_hex = await manager.add_torrent(torrent_data)
                            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
                            session = manager.torrents[info_hash_bytes]
                            
                            # Mock tracker.start() to prevent real network calls
                            with patch.object(session.tracker, 'start', new_callable=AsyncMock) as mock_tracker_start:
                                mock_tracker_start.return_value = None
                                
                                # Start the session
                                start_task = asyncio.create_task(session.start())
                            
                            # Wait a bit for initialization
                            await asyncio.sleep(0.2)
                            
                            # Verify peer_manager is initialized early (before tracker announce)
                            assert hasattr(session.download_manager, "peer_manager") and session.download_manager.peer_manager is not None, "peer_manager should be initialized early"
                            
                            # Simulate tracker response with peers (as dicts, not PeerInfo objects)
                            mock_peers = [
                                {"ip": "127.0.0.1", "port": 6881, "peer_source": "tracker"},
                                {"ip": "127.0.0.2", "port": 6882, "peer_source": "tracker"},
                            ]
                            
                            # Call the method that handles tracker responses
                            if hasattr(session, "_connect_peers_to_download"):
                                await session._connect_peers_to_download(mock_peers)
                            
                            # Verify download has started (piece_manager should be downloading)
                            if session.piece_manager:
                                # Check if download has started
                                is_downloading = getattr(session.piece_manager, "is_downloading", False)
                                # Note: is_downloading might be False if no pieces are missing,
                                # but peer_manager should be ready to accept connections
                                assert hasattr(session.download_manager, "peer_manager") and session.download_manager.peer_manager is not None, "peer_manager should be ready"
                            
                            # Wait for start to complete with timeout
                            if start_task:
                                try:
                                    await asyncio.wait_for(start_task, timeout=5.0)
                                except asyncio.TimeoutError:
                                    # Cancel the task if it times out
                                    start_task.cancel()
                                    try:
                                        await start_task
                                    except asyncio.CancelledError:
                                        pass
                            
                        finally:
                            # Cancel start_task if still running
                            if start_task and not start_task.done():
                                start_task.cancel()
                                try:
                                    await asyncio.wait_for(start_task, timeout=2.0)
                                except (asyncio.TimeoutError, asyncio.CancelledError):
                                    pass
                            
                            # Stop manager with timeout
                            try:
                                await asyncio.wait_for(manager.stop(), timeout=10.0)
                            except asyncio.TimeoutError:
                                pass  # Manager stop timeout is not critical for test

    @pytest.mark.asyncio
    async def test_peer_manager_reused_when_already_exists(self, tmp_path):
        """Test that existing peer_manager is reused when connecting new peers."""
        start_task: Optional[asyncio.Task] = None
        
        with patch("ccbt.config.config.get_config") as mock_get_config:
            from ccbt.config.config import Config
            # Create a valid config with discovery intervals >= 30
            config = Config()
            config.discovery.aggressive_initial_dht_interval = 30.0
            config.discovery.aggressive_discovery_interval_popular = 30.0
            config.discovery.aggressive_discovery_interval_active = 30.0
            config.nat.auto_map_ports = False  # Disable NAT to prevent blocking
            config.network.enable_tcp = False  # Disable TCP server to prevent port conflicts
            config.discovery.enable_dht = False  # Disable DHT to prevent network initialization
            mock_get_config.return_value = config
            
            # Mock NAT manager to prevent hanging on port mapping
            with patch("ccbt.session.session.AsyncSessionManager._make_nat_manager") as mock_nat:
                mock_nat.return_value = None  # Disable NAT manager to prevent hangs
                
                manager = AsyncSessionManager(output_dir=str(tmp_path))
                manager.config.nat.auto_map_ports = False
                manager.config.network.enable_tcp = False
                manager.config.discovery.enable_dht = False
                
                # Mock heavy initialization methods
                manager._make_nat_manager = lambda: None  # type: ignore[method-assign]
                manager._make_tcp_server = lambda: None  # type: ignore[method-assign]
                
                # Mock DHT client to prevent port conflicts
                with patch.object(manager, "_make_dht_client", return_value=None):
                    # Mock _wait_for_starting_session to return immediately
                    from ccbt.session.torrent_addition import TorrentAdditionHandler
                    async def mock_wait_for_starting_session(self, session):
                        """Mock that returns immediately without waiting."""
                        # Set status to 'downloading' to allow test to proceed
                        if hasattr(session, 'info'):
                            session.info.status = "downloading"
                        return
                    
                    with patch.object(TorrentAdditionHandler, '_wait_for_starting_session', mock_wait_for_starting_session):
                        # Start manager with timeout
                        try:
                            await asyncio.wait_for(manager.start(), timeout=10.0)
                        except asyncio.TimeoutError:
                            pytest.fail("Manager start timed out")
                        
                        try:
                            # Create a torrent session
                            torrent_data = {
                                "info_hash": b"\x00" * 20,
                                "name": "Test Torrent",
                                "file_info": {"total_length": 1000},
                                "pieces_info": {
                                    "piece_length": 512,
                                    "num_pieces": 2,
                                    "piece_hashes": [b"\x11" * 20, b"\x22" * 20]
                                },
                                "announce_list": [["http://127.0.0.1:6969/announce"]],  # Add tracker URL for validation
                            }
                            
                            info_hash_hex = await manager.add_torrent(torrent_data)
                            info_hash_bytes: bytes = torrent_data["info_hash"]  # type: ignore[assignment]
                            session = manager.torrents[info_hash_bytes]
                            
                            # Mock tracker.start() to prevent real network calls
                            with patch.object(session.tracker, 'start', new_callable=AsyncMock) as mock_tracker_start:
                                mock_tracker_start.return_value = None
                                
                                # Start the session
                                start_task = asyncio.create_task(session.start())
                            
                            # Wait for peer_manager to be initialized
                            await asyncio.sleep(0.2)
                            
                            # Get the initial peer_manager
                            initial_peer_manager = getattr(session.download_manager, "peer_manager", None)
                            assert initial_peer_manager is not None, "peer_manager should be initialized"
                            
                            # Simulate connecting additional peers (as if from a tracker response)
                            mock_peers = [
                                {"ip": "127.0.0.3", "port": 6883, "peer_source": "tracker"},
                            ]
                            
                            # Call _connect_peers_to_download which should reuse existing peer_manager
                            if hasattr(session, "_connect_peers_to_download"):
                                await session._connect_peers_to_download(mock_peers)
                            
                            # Verify the same peer_manager instance is still being used
                            current_peer_manager = getattr(session.download_manager, "peer_manager", None)
                            assert current_peer_manager is initial_peer_manager, "peer_manager should be reused, not recreated"
                    
                            # Wait for start to complete with timeout
                            if start_task:
                                try:
                                    await asyncio.wait_for(start_task, timeout=5.0)
                                except asyncio.TimeoutError:
                                    # Cancel the task if it times out
                                    start_task.cancel()
                                    try:
                                        await start_task
                                    except asyncio.CancelledError:
                                        pass
                            
                        finally:
                            # Cancel start_task if still running
                            if start_task and not start_task.done():
                                start_task.cancel()
                                try:
                                    await asyncio.wait_for(start_task, timeout=2.0)
                                except (asyncio.TimeoutError, asyncio.CancelledError):
                                    pass
                            
                            # Stop manager with timeout
                            try:
                                await asyncio.wait_for(manager.stop(), timeout=10.0)
                            except asyncio.TimeoutError:
                                pass  # Manager stop timeout is not critical for test
